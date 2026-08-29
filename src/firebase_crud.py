from __future__ import annotations
import logging
import time
import uuid
from urllib.parse import quote
from typing import Sequence

import requests
from src.config import load_config

logger = logging.getLogger(__name__)


class FirebaseCRUD:
    _RETRY_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 0.5

    def __init__(self, auth=None, project_id: str | None = None, database_id: str = "(default)"):
        if project_id is None:
            cfg = load_config()
            project_id = cfg.get("firebase", {}).get("project_id", "")
        self._auth = auth
        self._project_id = project_id or ""
        self._database_id = database_id
        self._session = requests.Session()
        self._available = bool(self._project_id and self._auth)
        self._last_status: int | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self):
        return None

    @property
    def _documents_url(self) -> str:
        project = quote(self._project_id, safe="")
        database = quote(self._database_id, safe="")
        return f"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents"

    @property
    def _database_url(self) -> str:
        project = quote(self._project_id, safe="")
        database = quote(self._database_id, safe="")
        return f"https://firestore.googleapis.com/v1/projects/{project}/databases/{database}"

    def _token(self) -> str | None:
        return self._auth.get_valid_token() if self._auth else None

    def _request(self, method: str, path: str = "", **kwargs):
        token = self._token()
        if not token:
            self._last_status = 401
            return None
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")
        url = (
            path
            if path.startswith("https://")
            else f"{self._documents_url}/{path}" if path else self._documents_url
        )
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
    def _encode_value(value):
        if value is None:
            return {"nullValue": None}
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int):
            return {"integerValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, str):
            return {"stringValue": value}
        if isinstance(value, list):
            return {"arrayValue": {"values": [FirebaseCRUD._encode_value(item) for item in value]}}
        if isinstance(value, dict):
            return {"mapValue": {"fields": FirebaseCRUD._encode_fields(value)}}
        raise TypeError(f"Unsupported Firestore value: {type(value).__name__}")

    @staticmethod
    def _encode_fields(data: dict) -> dict:
        return {key: FirebaseCRUD._encode_value(value) for key, value in data.items()}

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
    def _document_path(collection: str, doc_id: str | None = None) -> str:
        parts = [quote(part, safe="") for part in collection.strip("/").split("/") if part]
        if doc_id is not None:
            parts.append(quote(doc_id, safe=""))
        return "/".join(parts)

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
                    logger.debug("Retry %d/%d for %s in %ss after: %s",
                                 attempt, self._RETRY_ATTEMPTS, fn.__name__, delay, e)
                    time.sleep(delay)
        logger.warning("%s failed after %d attempts: %s",
                       fn.__name__, self._RETRY_ATTEMPTS, last_error)
        return None

    def get(self, collection: str, doc_id: str) -> dict | None:
        def _do():
            response = self._request("GET", self._document_path(collection, doc_id))
            if response is None or response.status_code == 404:
                return None
            response.raise_for_status()
            return self._decode_fields(response.json().get("fields", {}))
        return self._with_retry(_do)

    def set(self, collection: str, doc_id: str, data: dict, merge: bool = True) -> bool:
        def _do():
            path = self._document_path(collection, doc_id)
            params = [("updateMask.fieldPaths", key) for key in data] if merge else None
            response = self._request(
                "PATCH", path, params=params,
                json={"name": f"{self._documents_url}/{path}", "fields": self._encode_fields(data)},
            )
            if response is None:
                return False
            response.raise_for_status()
            return True
        result = self._with_retry(_do)
        return bool(result)

    def add(self, collection: str, data: dict) -> str | None:
        def _do():
            response = self._request("POST", self._document_path(collection), json={"fields": self._encode_fields(data)})
            if response is None:
                return None
            response.raise_for_status()
            return response.json().get("name", "").rsplit("/", 1)[-1] or None
        return self._with_retry(_do)

    def batch_add(self, collection: str, items: list[dict]) -> bool:
        def _do():
            writes = []
            for data in items:
                path = self._document_path(collection, uuid.uuid4().hex)
                writes.append({
                    "update": {
                        "name": f"{self._documents_url}/{path}",
                        "fields": self._encode_fields(data),
                    }
                })
            response = self._request(
                "POST", f"{self._database_url}:commit", json={"writes": writes}
            )
            if response is None:
                return False
            response.raise_for_status()
            return True
        return bool(self._with_retry(_do))

    def delete(self, collection: str, doc_id: str) -> bool:
        def _do():
            response = self._request("DELETE", self._document_path(collection, doc_id))
            if response is None:
                return False
            response.raise_for_status()
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
            parts = collection.strip("/").split("/")
            parent = "/".join(parts[:-1])
            collection_id = parts[-1]
            structured_query: dict[str, object] = {"from": [{"collectionId": collection_id}]}
            if order_by:
                structured_query["orderBy"] = [{
                    "field": {"fieldPath": order_by},
                    "direction": "ASCENDING" if ascending else "DESCENDING",
                }]
            if limit:
                structured_query["limit"] = limit
            query_path = f"{parent}:runQuery" if parent else ":runQuery"
            response = self._request("POST", query_path, json={"structuredQuery": structured_query})
            if response is None:
                return []
            response.raise_for_status()
            rows = response.json()
            return [self._decode_fields(row.get("document", {}).get("fields", {})) for row in rows if row.get("document")]
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
        """Run a Firestore REST kNN query with an optional category filter."""
        if not vector:
            raise ValueError("vector must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if distance_measure not in {"COSINE", "EUCLIDEAN", "DOT_PRODUCT"}:
            raise ValueError("unsupported distance measure")
        if (category_field is None) != (category_value is None):
            raise ValueError("category_field and category_value must be provided together")

        def _do():
            parts = collection.strip("/").split("/")
            parent = "/".join(parts[:-1])
            collection_id = parts[-1]
            structured_query: dict[str, object] = {
                "from": [{"collectionId": collection_id}],
                "findNearest": {
                    "vectorField": {"fieldPath": vector_field},
                    "queryVector": {
                        "mapValue": {
                            "fields": {
                                "__type__": {"stringValue": "__vector__"},
                                "value": {
                                    "arrayValue": {
                                        "values": [
                                            {"doubleValue": float(value)}
                                            for value in vector
                                        ]
                                    }
                                },
                            }
                        }
                    },
                    "distanceMeasure": distance_measure,
                    "limit": limit,
                    "distanceResultField": "vector_distance",
                },
            }
            if category_field is not None:
                structured_query["where"] = {
                    "fieldFilter": {
                        "field": {"fieldPath": category_field},
                        "op": "EQUAL",
                        "value": self._encode_value(category_value),
                    }
                }
            query_path = f"{parent}:runQuery" if parent else ":runQuery"
            response = self._request(
                "POST",
                query_path,
                json={"structuredQuery": structured_query},
            )
            if response is None:
                return []
            response.raise_for_status()
            results = []
            for row in response.json():
                document = row.get("document")
                if not document:
                    continue
                item = self._decode_fields(document.get("fields", {}))
                item.setdefault("id", document.get("name", "").rsplit("/", 1)[-1])
                results.append(item)
            return results

        result = self._with_retry(_do)
        return result or []
