from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.firebase_crud import FirebaseCRUD


@pytest.fixture
def auth() -> MagicMock:
    instance = MagicMock()
    instance.get_valid_token.return_value = "test-token"
    return instance


@pytest.fixture
def crud(auth: MagicMock) -> FirebaseCRUD:
    return FirebaseCRUD(auth=auth, project_id="test-project")


# ── get ─────────────────────────────────────────────────────────────────────

def test_get_document_exists(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"fields": {"key": {"stringValue": "val"}}}
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    result = crud.get("c", "d")
    assert result == {"key": "val"}
    call = crud._session.request.call_args
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_get_document_not_found(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=404)
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    result = crud.get("c", "missing")
    assert result is None


def test_get_network_error_returns_none(crud: FirebaseCRUD, monkeypatch) -> None:
    monkeypatch.setattr(crud._session, "request", MagicMock(side_effect=Exception("timeout")))

    result = crud.get("c", "d")
    assert result is None
    assert crud.available


# ── set ─────────────────────────────────────────────────────────────────────

def test_set_no_merge(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)
    ok = crud.set("c", "d", {"key": "val"}, merge=False)
    assert ok is True
    assert request.call_args.kwargs["json"]["fields"]["key"] == {"stringValue": "val"}


def test_set_with_merge_preserves_existing(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)
    ok = crud.set("c", "d", {"key": "new"}, merge=True)
    assert ok is True
    assert request.call_args.kwargs["params"] == [("updateMask.fieldPaths", "key")]


# ── add ─────────────────────────────────────────────────────────────────────

def test_add_document(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"name": "projects/test-project/databases/(default)/documents/c/auto123"}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    doc_id = crud.add("c", {"text": "hello"})
    assert doc_id == "auto123"
    assert request.call_args.kwargs["json"]["fields"]["text"] == {"stringValue": "hello"}


# ── delete ──────────────────────────────────────────────────────────────────

def test_delete_document(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))
    ok = crud.delete("c", "d")
    assert ok is True


# ── query ───────────────────────────────────────────────────────────────────

def test_query_collection(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = [
        {"document": {"fields": {"x": {"stringValue": "a"}}}},
        {"document": {"fields": {"x": {"stringValue": "b"}}}},
    ]
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    docs = crud.query("c")
    assert len(docs) == 2
    assert docs[0]["x"] == "a"
    assert docs[1]["x"] == "b"


def test_query_empty_collection(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = []
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    docs = crud.query("c")
    assert docs == []


# ── read_all_text ───────────────────────────────────────────────────────────

def test_read_all_text(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = [
        {"document": {"fields": {"text": {"stringValue": "hello"}}}},
        {"document": {"fields": {"text": {"stringValue": "world"}}}},
    ]
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    texts = crud.read_all_text("c")
    assert texts == ["hello", "world"]


# ── retry ───────────────────────────────────────────────────────────────────

def test_retry_succeeds_on_second_attempt(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"fields": {"x": {"stringValue": "y"}}}
    request = MagicMock(side_effect=[Exception("fail"), response])
    monkeypatch.setattr(crud._session, "request", request)

    result = crud.get("c", "d")
    assert result == {"x": "y"}
    assert request.call_count == 2


# ── unavailable recovery ────────────────────────────────────────────────────

def test_unavailable_without_auth() -> None:
    assert not FirebaseCRUD(project_id="test-project").available


def test_add_returns_none_when_no_auth() -> None:
    crud = FirebaseCRUD(project_id="test-project")
    result = crud.add("c", {"text": "hello"})
    assert result is None
    assert not crud.available
