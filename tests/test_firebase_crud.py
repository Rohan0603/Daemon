from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.firebase_crud import FirebaseCRUD


@pytest.fixture
def crud() -> FirebaseCRUD:
    return FirebaseCRUD(creds_path="dummy/path")


# ── Field flattening ────────────────────────────────────────────────────────

def test_flatten_fields(crud: FirebaseCRUD) -> None:
    fields = {
        "name": {"stringValue": "Daemon"},
        "age": {"integerValue": "42"},
        "score": {"doubleValue": 3.14},
        "active": {"booleanValue": True},
        "tags": {"arrayValue": {"values": [{"stringValue": "a"}, {"stringValue": "b"}]}},
        "nothing": {"nullValue": None},
    }
    flat = crud._flatten_fields(fields)
    assert flat["name"] == "Daemon"
    assert flat["age"] == 42
    assert flat["score"] == 3.14
    assert flat["active"] is True
    assert flat["tags"] == ["a", "b"]
    assert flat["nothing"] is None


def test_unflatten_fields(crud: FirebaseCRUD) -> None:
    data = {"name": "Daemon", "age": 42, "score": 3.14, "active": True}
    fields = crud._unflatten_fields(data)
    assert fields["name"]["stringValue"] == "Daemon"
    assert fields["age"]["integerValue"] == "42"


def test_flatten_document(crud: FirebaseCRUD) -> None:
    doc = {"fields": {"x": {"stringValue": "y"}}}
    result = crud._flatten_document(doc)
    assert result["x"] == "y"


# ── get ─────────────────────────────────────────────────────────────────────

def test_get_document_exists(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "fields": {"key": {"stringValue": "val"}},
    }
    with patch("requests.get", return_value=mock_resp):
        result = crud.get("c", "d")
    assert result == {"key": "val"}


def test_get_document_not_found(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.get", return_value=mock_resp):
        result = crud.get("c", "missing")
    assert result is None


def test_get_network_error_sets_unavailable(crud: FirebaseCRUD) -> None:
    with patch("requests.get", side_effect=Exception("timeout")):
        result = crud.get("c", "d")
    assert result is None
    assert not crud.available


def test_get_401_sets_unavailable(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.get", return_value=mock_resp):
        result = crud.get("c", "d")
    assert result is None
    assert not crud.available


# ── set ─────────────────────────────────────────────────────────────────────

def test_set_no_merge(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.patch", return_value=mock_resp) as mock_patch:
        ok = crud.set("c", "d", {"key": "val"}, merge=False)
    assert ok is True
    body = mock_patch.call_args[1]["json"]
    assert body["fields"]["key"]["stringValue"] == "val"


def test_set_with_merge_preserves_existing(crud: FirebaseCRUD) -> None:
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {
        "fields": {"existing": {"stringValue": "e"}, "key": {"stringValue": "old"}},
    }
    patch_resp = MagicMock()
    patch_resp.status_code = 200

    with patch("requests.get", return_value=get_resp), \
         patch("requests.patch", return_value=patch_resp) as mock_patch:
        ok = crud.set("c", "d", {"key": "new"}, merge=True)
    assert ok is True
    body = mock_patch.call_args[1]["json"]
    assert body["fields"]["existing"]["stringValue"] == "e"
    assert body["fields"]["key"]["stringValue"] == "new"


def test_set_merge_when_doc_missing(crud: FirebaseCRUD) -> None:
    get_resp = MagicMock()
    get_resp.status_code = 404
    patch_resp = MagicMock()
    patch_resp.status_code = 200

    with patch("requests.get", return_value=get_resp), \
         patch("requests.patch", return_value=patch_resp) as mock_patch:
        ok = crud.set("c", "d", {"key": "val"}, merge=True)
    assert ok is True
    body = mock_patch.call_args[1]["json"]
    assert body["fields"]["key"]["stringValue"] == "val"


# ── add ─────────────────────────────────────────────────────────────────────

def test_add_document(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"name": "projects/p/databases/d/documents/c/auto123"}
    with patch("requests.post", return_value=mock_resp) as mock_post:
        doc_id = crud.add("c", {"text": "hello"})
    assert doc_id == "auto123"
    mock_post.assert_called_once()


# ── delete ──────────────────────────────────────────────────────────────────

def test_delete_document(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.delete", return_value=mock_resp):
        ok = crud.delete("c", "d")
    assert ok is True


def test_delete_missing(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.delete", return_value=mock_resp):
        ok = crud.delete("c", "missing")
    assert ok is False


# ── query ───────────────────────────────────────────────────────────────────

def test_query_collection(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "documents": [
            {"fields": {"x": {"stringValue": "a"}}},
            {"fields": {"x": {"stringValue": "b"}}},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        docs = crud.query("c")
    assert len(docs) == 2
    assert docs[0]["x"] == "a"


def test_query_empty_collection(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    with patch("requests.get", return_value=mock_resp):
        docs = crud.query("c")
    assert docs == []


# ── read_all_text ───────────────────────────────────────────────────────────

def test_read_all_text(crud: FirebaseCRUD) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "documents": [
            {"fields": {"text": {"stringValue": "hello"}}},
            {"fields": {"text": {"stringValue": "world"}}},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        texts = crud.read_all_text("c")
    assert texts == ["hello", "world"]


# ── retry ───────────────────────────────────────────────────────────────────

def test_retry_succeeds_on_second_attempt(crud: FirebaseCRUD) -> None:
    fail_resp = MagicMock()
    fail_resp.status_code = 500
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"fields": {"x": {"stringValue": "y"}}}

    with patch("requests.get", side_effect=[fail_resp, ok_resp]) as mock_get:
        result = crud.get("c", "d")
    assert result == {"x": "y"}
    assert mock_get.call_count == 2


# ── unavailable recovery ────────────────────────────────────────────────────

def test_available_resets_on_new_crud() -> None:
    """A new instance should start as available."""
    c = FirebaseCRUD(creds_path="dummy/path")
    assert c.available


def test_add_returns_none_when_no_auth(crud: FirebaseCRUD) -> None:
    crud._available = False
    result = crud.add("c", {"text": "hello"})
    assert result is None
    assert not crud.available
